(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x254 (bvshl y (_ bv23 32))))
(let ((?x250 (bvshl x (_ bv23 32))))
(let ((?x257 (bvsub ?x250 ?x254)))
(let ((?x24 (bvsub x y)))
(let ((?x256 (bvshl ?x24 (_ bv23 32))))
(and (distinct ?x256 ?x257) true)))))))
(check-sat)
