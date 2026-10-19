(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x174 (bvshl y (_ bv14 32))))
(let ((?x170 (bvshl x (_ bv14 32))))
(let ((?x175 (bvadd ?x170 ?x174)))
(let ((?x19 (bvadd x y)))
(let ((?x173 (bvshl ?x19 (_ bv14 32))))
(and (distinct ?x173 ?x175) true)))))))
(check-sat)
