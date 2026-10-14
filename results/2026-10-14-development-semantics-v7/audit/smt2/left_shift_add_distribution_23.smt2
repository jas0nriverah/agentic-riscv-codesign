(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x254 (bvshl y (_ bv23 32))))
(let ((?x250 (bvshl x (_ bv23 32))))
(let ((?x255 (bvadd ?x250 ?x254)))
(let ((?x19 (bvadd x y)))
(let ((?x253 (bvshl ?x19 (_ bv23 32))))
(and (distinct ?x253 ?x255) true)))))))
(check-sat)
