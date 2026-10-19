(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x272 (bvshl y (_ bv25 32))))
(let ((?x268 (bvshl x (_ bv25 32))))
(let ((?x273 (bvadd ?x268 ?x272)))
(let ((?x19 (bvadd x y)))
(let ((?x271 (bvshl ?x19 (_ bv25 32))))
(and (distinct ?x271 ?x273) true)))))))
(check-sat)
