(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x174 (bvshl y (_ bv14 32))))
(let ((?x170 (bvshl x (_ bv14 32))))
(let ((?x177 (bvsub ?x170 ?x174)))
(let ((?x24 (bvsub x y)))
(let ((?x176 (bvshl ?x24 (_ bv14 32))))
(and (distinct ?x176 ?x177) true)))))))
(check-sat)
