(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x77 (bvshl y (_ bv3 32))))
(let ((?x73 (bvshl x (_ bv3 32))))
(let ((?x78 (bvadd ?x73 ?x77)))
(let ((?x19 (bvadd x y)))
(let ((?x76 (bvshl ?x19 (_ bv3 32))))
(and (distinct ?x76 ?x78) true)))))))
(check-sat)
