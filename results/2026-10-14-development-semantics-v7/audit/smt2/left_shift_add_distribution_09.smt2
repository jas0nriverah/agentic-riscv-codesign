(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x129 (bvshl y (_ bv9 32))))
(let ((?x125 (bvshl x (_ bv9 32))))
(let ((?x130 (bvadd ?x125 ?x129)))
(let ((?x19 (bvadd x y)))
(let ((?x128 (bvshl ?x19 (_ bv9 32))))
(and (distinct ?x128 ?x130) true)))))))
(check-sat)
